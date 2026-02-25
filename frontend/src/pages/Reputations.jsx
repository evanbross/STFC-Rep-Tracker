import React, { useState, useEffect } from 'react';
import axios from 'axios';

const RepTable = ({ title, data, loading }) => (
  <div className="container">
    <h2>{title}</h2>
    <table>
      <thead>
        <tr>
          <th>Name</th>
          <th className="text-right">Low Limit</th>
          <th className="text-right">High Limit</th>
        </tr>
      </thead>
      <tbody>
        {loading ? (
          <tr><td colSpan="3">Loading...</td></tr>
        ) : data.length === 0 ? (
          <tr><td colSpan="3">No reputations found.</td></tr>
        ) : data.map((rep, idx) => (
          <tr key={idx}>
            <td>{rep.name}</td>
            <td className="text-right">{rep.low_limit?.toLocaleString()}</td>
            <td className="text-right">
              {rep.high_limit !== null && rep.high_limit !== undefined ? rep.high_limit.toLocaleString() : '-'}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  </div>
);

const Reputations = () => {
  const [fkrData, setFkrData] = useState([]);
  const [augmentData, setAugmentData] = useState([]);
  const [rogueData, setRogueData] = useState([]);
  const [bajoranData, setBajoranData] = useState([]);
  const [terranData, setTerranData] = useState([]);
  const [dtiData, setDtiData] = useState([]);
  const [section31Data, setSection31Data] = useState([]);
  const [exBorgData, setExBorgData] = useState([]);
  
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadAllReputations = async () => {
      setLoading(true);
      try {
        const [fkr, aug, rog, baj, ter, dti, s31, exb] = await Promise.all([
          axios.get('/api/reputations'),
          axios.get('/api/augment-reputations'),
          axios.get('/api/rogue-reputations'),
          axios.get('/api/bajoran-reputations'),
          axios.get('/api/terran-reputations'),
          axios.get('/api/dti-reputations'),
          axios.get('/api/section31-reputations'),
          axios.get('/api/ex-borg-reputations')
        ]);
        
        setFkrData(fkr.data);
        setAugmentData(aug.data);
        setRogueData(rog.data);
        setBajoranData(baj.data);
        setTerranData(ter.data);
        setDtiData(dti.data);
        setSection31Data(s31.data);
        setExBorgData(exb.data);
      } catch (error) {
        console.error('Error loading reputations:', error);
      } finally {
        setLoading(false);
      }
    };

    loadAllReputations();
  }, []);

  return (
    <div className="reputations-page">
      <h1>Reputation Tiers</h1>
      
      <RepTable title="FKR Reputation Tiers" data={fkrData} loading={loading} />
      <RepTable title="Augment Reputation Tiers" data={augmentData} loading={loading} />
      <RepTable title="Rogue Reputation Tiers" data={rogueData} loading={loading} />
      <RepTable title="Bajoran Reputation Tiers" data={bajoranData} loading={loading} />
      <RepTable title="Terran Reputation Tiers" data={terranData} loading={loading} />
      <RepTable title="DTI Reputation Tiers" data={dtiData} loading={loading} />
      <RepTable title="Section 31 Reputation Tiers" data={section31Data} loading={loading} />
      <RepTable title="Ex-Borg Reputation Tiers" data={exBorgData} loading={loading} />
    </div>
  );
};

export default Reputations;
